import geopandas as gpd
import pandas as pd
import os
import xarray as xr
from tqdm import tqdm
import glob

############ FUNÇÕES
def processar_municipio(mun, T2_xr, outPathInter):
    """
    Recorte do campo de temperatura gradeado utilizando a
    geometria do município, calcula a média espacial da temperatura
    para cada passo de tempo e grava os resultados em arquivos CSV
    mensais.

    Parameters
    ----------
    T2_xr : xarray.DataArray
        Dataset de temperatura do ar gradeado, contendo as dimensões
        'time', 'x' e 'y', e um sistema de referência de coordenadas
        compatível com o rioxarray.
    mun : object
        Itineração do município contendo os dados do município analisado
    outPathInter : str
        Diretório base de saída onde os arquivos CSV de temperatura
        serão armazenados.

    Return
    -------
    None
    """
    # Recorte o campo de temperatura (T2) usando a geometria do município.
    temp_clip = T2_xr.rio.clip(
        [mun.geometry],
        T2_xr.rio.crs,
        drop=True,
        all_touched=True
    )

    # Calcula a média espacial da temperatura para cada passo de tempo em todas as dimensões
    temp_vals = temp_clip.mean(dim=("x", "y")).values

    df_rows = []

    # Loop sobre todos os passos de tempo do dataset original
    for ii, date in enumerate(T2_xr["time"].values):

        # Converte o timestamp para datetime do pandas
        dt = pd.to_datetime(date)

        # Cria um DataFrame com uma única linha para o tempo específico
        df_row = pd.DataFrame([{
            "CD_MUN": mun["CD_MUN"],
            "year":  dt.year,
            "month": dt.month,
            "day":   dt.day,
            "hour":  dt.hour,
            "TEMP_C": float(temp_vals[ii]),
        }])

        df_rows.append(df_row)

    return pd.concat(df_rows)
