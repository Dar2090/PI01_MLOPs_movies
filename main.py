from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()


@app.get("/")
def read_root():
    html_content = """
    <html>
        <head>
            <title>Darwin API</title>
        </head>
        <body>
            <h1>Bienvenidos a mi API</h1>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# -------------------------------------------------------------------------------

# Cargamos nuestro archivo CSV para ser consumido por los endpoints de consultas:
df_red = pd.read_csv('Datasets/movies_dataset_red.csv', low_memory=False)


@app.get('/peliculas_mes/{mes}')
def peliculas_mes(mes: str) -> dict:
    # Diccionario para hacer la traduccion de nombres de mes de español a ingles
    meses_dict = {"enero":"January", "febrero":"February", "marzo":"March", "abril":"April", "mayo":"May", "junio":"June",
                  "julio":"July", "agosto":"August", "septiembre":"September", "octubre":"October", "noviembre":"November",
                  "diciembre":"December"}
    
    # Convierte la columna "release_date" a formato de fecha
    df_red["release_date"] = pd.to_datetime(df_red["release_date"], errors="coerce")

    # Traduce el nombre de mes ingresado a su equivalente en ingles
    mes_en = meses_dict.get(mes.lower(), None)
    if mes_en is None:
        return {"Error": "El mes ingresado no es válido"}

    # Filtra las películas que se estrenaron en el mes especificado
    peliculas_filtradas = df_red[df_red["release_date"].dt.month == pd.to_datetime(mes_en, format="%B").month]

    # Cuenta la cantidad de películas filtradas
    cantidad_peliculas = len(peliculas_filtradas)

    # Traduce el nombre del mes en ingles de vuelta a español
    mes_es = [key for key, value in meses_dict.items() if value == mes_en][0]

    return {"mes": mes_es.capitalize(), 
            "cantidad": cantidad_peliculas}


@app.get('/peliculas_dia/{dia}')
def peliculas_dia(dia: str) -> dict:
  
    dia_num = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'].index(dia)

    # Convertimos la columna 'release_date' a datetime (just in case)
    df_red['release_date'] = pd.to_datetime(df_red['release_date'], format='%Y-%m-%d')

    # Filtramos películas que se estrenaron en el día de la semana dado
    peliculas_en_dia = df_red[df_red['release_date'].dt.weekday == dia_num]

    # Filtramos películas que tengan una fecha de estreno válida
    peliculas_con_fecha_valida = peliculas_en_dia[peliculas_en_dia['release_date'].notnull()]

    cantidad = peliculas_con_fecha_valida.shape[0]

    # Retornar un diccionario con el día y la cantidad de películas
    return {'dia': dia, 
            'cantidad': cantidad}


@app.get('/franquicia/{franquicia}')
def franquicia(franquicia: str) -> dict:
   
    # Filtramos las películas que pertenecen a la franquicia solicitada
    peliculas_filtradas = df_red[df_red["belongs_to_collection"] == franquicia]

    # Contamos la cantidad de películas
    cantidad_peliculas = len(peliculas_filtradas)

    # Calculamos la ganancia total
    ganancia_total = peliculas_filtradas["revenue"].sum()

    # Calculamos la ganancia promedio
    ganancia_promedio = ganancia_total / cantidad_peliculas

    return {'franquicia': franquicia,
            'cantidad': cantidad_peliculas,
            'ganancia_total': ganancia_total,
            'ganancia_promedio': ganancia_promedio}


@app.get('/peliculas_pais/{pais}')
def peliculas_pais(pais: str) -> dict:

    # Filtramos las películas que se produjeron en el país solicitado
    peliculas_filtradas = df_red[df_red["production_countries"].str.contains(pais)]

    # Contamos la cantidad de películas
    cantidad_peliculas = len(peliculas_filtradas)

    return {'pais': pais,
            'cantidad': cantidad_peliculas}


@app.get('/productoras/{productora}')
def productoras(productora: str):
    # Crear subconjunto del DataFrame original para la productora seleccionada
    subset = df_red[df_red["production_companies"].str.contains(productora, na=False)]

    # Obtener la ganancia total y la cantidad de películas producidas por la productora seleccionada
    ganancia_total = subset["revenue"].sum()
    cantidad = len(subset)

    # Retornar un diccionario con los resultados
    return {"productora": productora, 
            "ganancia_total": ganancia_total, 
            "cantidad": cantidad}


@app.get('/retorno/{pelicula}')
def retorno(pelicula: str):
    # Crear subconjunto del DataFrame original para la película seleccionada
    subset = df_red[df_red["title"] == pelicula]

    # Verificar si el subconjunto tiene al menos un elemento
    if len(subset) == 0:
        return {'error': 'Película no encontrada'}

    # Obtener la inversión, ganancia y año de lanzamiento de la película seleccionada
    inversion = subset["budget"].values[0]
    ganancia = subset["revenue"].values[0] - inversion
    anio = str(subset["release_year"].values[0])

    # Obtener el retorno de la película seleccionada a partir de la columna "return"
    retorno = subset["return"].values[0]

    # Retornar un diccionario con los resultados
    return {'pelicula': pelicula, 
            'inversion': inversion, 
            'ganancia': ganancia, 
            'retorno': retorno, 
            'anio': anio}

# -------------------------------------------------------------------------------

# Cargamos nuestro archivo CSV para ser consumido por el endpoint de ML:
df2 = pd.read_csv('Datasets/movies_ML_sample10.csv', low_memory=False)

# Cargamos nuestro modelo:

# Tratar los valores faltantes, si los hubiera
df2.fillna({'genres': 'Unknown', 'overview': ''}, inplace=True)

# Codificación one-hot para la columna 'genres'
one_hot_encoder = OneHotEncoder(sparse=False)
genres_encoded = one_hot_encoder.fit_transform(df2[['genres']])

# Crear una matriz de características dispersa para el resumen (overview) utilizando TF-IDF
vectorizer = TfidfVectorizer()
overview_features = vectorizer.fit_transform(df2['overview'])

# Concatenar las matrices de características y las características categóricas
features_matrix = hstack([overview_features, genres_encoded])

# Calcular la similitud del coseno entre las características
similarity_matrix = cosine_similarity(features_matrix)

# Crear un diccionario que mapee el título de la película a su índice en el DataFrame
title_to_index = {title: index for index, title in enumerate(df2['title'])}

@app.get('/recomendacion/{titulo}')
def recomendacion(titulo: str, top_n=5):
    # Obtener el índice de la película objetivo
    movie_index = title_to_index[titulo]

    # Obtener la fila de similitud correspondiente a la película objetivo
    similarity_scores = similarity_matrix[movie_index]

    # Obtener los índices de las películas más similares
    top_indices = similarity_scores.argsort()[::-1][1:int(top_n)+1]

    # Obtener los títulos de las películas recomendadas
    recommended_movies = df2.iloc[top_indices]['title'].values.tolist()

    return {'Lista recomendada': recommended_movies}

