"""
Module for processing and calculating evaporative emissions associated with
the use of automotive fuels (Gasoline C and Hydrous Ethanol) at fuel stations in Brazil.

This file gathers a set of functions aimed at filtering,
standardizing, and integrating data from different sources,
allowing the estimation of evaporation emissions during stages such as:

- Storage tank breathing,
- Vehicle refueling (vehicle filling).

Author: Marcos Perrude  
Date: October 9, 2025
"""

import geopandas as gpd
import re
import os
import pandas as pd
from scipy.optimize import curve_fit
import numpy as np

# Function to format CNPJ only if necessary
def format_cnpj(cnpj):
    """
    Formats a CNPJ to the standard XX.XXX.XXX/XXXX-XX,
    if it is not already formatted.

    Parameters
    ----------
    cnpj : str or int
        Raw or formatted CNPJ.

    Returns
    -------
    str
        Formatted CNPJ.
    """
    
    cnpj_str = str(cnpj)
    # Regex to detect CNPJ already formatted in the standard pattern
    if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", cnpj_str):
        return cnpj_str  # already formatted
    
    # Format if not already formatted
    else:
        cnpj_str = re.sub(r"\D", "", cnpj_str)  # remove everything that is not a digit
        cnpj_str = cnpj_str.zfill(14)  # ensure 14 digits
        return f"{cnpj_str[:2]}.{cnpj_str[2:5]}.{cnpj_str[5:8]}/{cnpj_str[8:12]}-{cnpj_str[12:]}"


# Function that selects fuel stations present in both IBAMA and ANP databases
def filtragempostos (postos_anp , postos_ibama):
    """
    Filters fuel stations that are simultaneously present
    in the ANP and IBAMA databases, adding geographic coordinates
    from IBAMA to the ANP data.

    Parameters
    ----------
    postos_anp : pandas.DataFrame
        ANP database.
    postos_ibama : pandas.DataFrame
        IBAMA database.

    Returns
    -------
    postos_anp_loc : Pandas.DataFrame
        DataFrame with stations with valid CNPJ and geographic coordinates.
    """
    
    postos_anp_loc  = postos_anp.copy()
    
    # Format CNPJ if necessary
    postos_anp_loc['CNPJ'] = postos_anp_loc['CNPJ'].apply(format_cnpj)

    # Assign IBAMA location only to stations that exist in ANP
    postos_anp_loc = postos_anp_loc.merge(
        postos_ibama[['CNPJ' , 'Latitude' , 'Longitude' ]],
        on =  'CNPJ',
        how = 'left'
        )
    
    # Drop stations that are not in IBAMA
    linhas_nan_lat = postos_anp_loc[postos_anp_loc['Latitude'].isna()]
    postos_anp_loc = postos_anp_loc.drop(linhas_nan_lat.index)
    return postos_anp_loc


# Function developed to select only MCIP cells that contain fuel stations
def filtragemcelulas(postos_ibama, postos_anp, desg_consumo_city, 
                     shp_cells, mun):
    """
    Filtering of cells that contain fuel stations only.
    Performs normalization of VKT values for these new cells.

    Parameters
    ----------
    postos_ibama : pandas.DataFrame
    postos_anp : pandas.DataFrame
    desg_consumo_city : pandas.DataFrame
        VKT data disaggregated by cell.
    shp_cells : geopandas.GeoDataFrame
        Spatial grid.

    Returns
    -------
    desg_filtrado : pandas.DataFrame
        Filtered and normalized VKT values only in cells with stations.
    """
    # desg_consumo_city = desg_consumo

        # CNPJ formatting
    postos_anp_loc = filtragempostos(postos_anp, postos_ibama)
        
        # Creation of geodataframe with latitude and longitude points
    gdf = gpd.GeoDataFrame(
            postos_anp_loc,
            geometry=gpd.points_from_xy(postos_anp_loc["Longitude"], postos_anp_loc["Latitude"]),
            crs=shp_cells.crs  )
    mun_postos = gpd.sjoin(gdf, mun, how='inner', predicate='within')
    mun_postos = mun_postos.drop(columns=['index_right'], errors='ignore')
    
    # gdf = mun_postos
    # Identification of the cells where each station falls           
    gdf_com_cells = gpd.sjoin(
            mun_postos, 
            shp_cells[["fid", "geometry"]], 
            how="left", 
            predicate="within")
    
    # Remove stations that did not fall within any cell
    gdf_com_cells = gdf_com_cells.dropna(subset=["fid"])
    # Convert fid to integer
    gdf_com_cells["fid"] = gdf_com_cells["fid"].astype(int)
    
    # Ensure consumption cell_id is integer with NaN support
    desg_consumo_city["cell_id"] = desg_consumo_city["cell_id"].astype("Int64")
    
    # Get list of cells that have at least one station
    celulas_com_postos = gdf_com_cells["fid"].unique()
    
    # Filter consumption DataFrame to include only these cells
    desg_filtrado = desg_consumo_city[
        desg_consumo_city["cell_id"].isin(celulas_com_postos)
        ]
    desg_filtrado['vkt_fraction_corrigido'] = desg_filtrado['vkt_fraction']/desg_filtrado['vkt_fraction'].sum()
    
    prop = len(gdf_com_cells['CNPJ'].unique()) / len(mun_postos['CNPJ'].unique())
    
    return desg_filtrado, prop


# Function to load the VKT of the analyzed city
def carregar_vkt_city(postos_ibama,postos_anp,desg_consumo, cidade, shp_cells,mun):
    """
    Loads and filters VKT data for a specific city,
    keeping only cells with fuel stations.

    Parameters
    ----------
    postos_anp : pandas.DataFrame
        ANP database.
    postos_ibama : pandas.DataFrame
        IBAMA database.
    desg_consumo_city : pandas.DataFrame
        VKT data disaggregated by cell.
    cidade : int
        IBGE municipality code.
    shp_cells : geopandas.GeoDataFrame
        Spatial grid.

    Returns
    -------
    desg_consumo_city : pandas.DataFrame
        Filtered and normalized VKT for the city.
    """
    # cidade = i
    # VKT filtering for the analyzed city
    desg_consumo_city = desg_consumo[
        desg_consumo["city_id"] == cidade
    ].sort_index()
            
    # Select only cells with stations
    desg_consumo_city , prop = filtragemcelulas(postos_ibama, postos_anp, 
                                         desg_consumo_city, shp_cells,mun)
        
    return desg_consumo_city , prop
# #%%
# import pandas as pd
# import geopandas as gpd
# import matplotlib.pyplot as plt

# # =============================================================================
# # AGREGA O VKT POR CÉLULA
# # =============================================================================

# cells_vkt = (
#     desg_consumo_city
#     .groupby('cell_id', as_index=False)['vkt_fraction']
#     .sum()
# )

# print('\nNúmero de células utilizadas:')
# print(len(cells_vkt))


# # =============================================================================
# # MERGE ENTRE DESAGREGAÇÃO E GRID
# # =============================================================================

# cells_plot = shp_cells.merge(
#     cells_vkt,
#     left_on='fid',
#     right_on='cell_id',
#     how='inner'
# )

# print('\nNúmero de células após merge:')
# print(len(cells_plot))

# print('\nFIDs selecionados:')
# print(sorted(cells_plot['fid'].unique()))


# # =============================================================================
# # TESTE: CÉLULAS DENTRO DO MUNICÍPIO
# # =============================================================================

# cells_within = gpd.sjoin(
#     cells_plot,
#     mun[['geometry']],
#     how='left',
#     predicate='within'
# )

# print('\nCélulas dentro do município:')
# print(cells_within['index_right'].notna().sum())

# print('Células fora do município:')
# print(cells_within['index_right'].isna().sum())


# # =============================================================================
# # PLOT 1 - GRID COMPLETO + MUNICÍPIO + CÉLULAS UTILIZADAS
# # =============================================================================

# fig, ax = plt.subplots(figsize=(12, 12))

# # Grid completo
# shp_cells.boundary.plot(
#     ax=ax,
#     color='lightgray',
#     linewidth=0.5,
#     label='Grid'
# )

# # Município
# mun.plot(
#     ax=ax,
#     facecolor='none',
#     edgecolor='black',
#     linewidth=2,
#     label='Município'
# )

# # Células utilizadas
# cells_plot.plot(
#     ax=ax,
#     column='vkt_fraction',
#     cmap='Reds',
#     edgecolor='red',
#     linewidth=1.5,
#     legend=True,
#     legend_kwds={'label': 'VKT fraction acumulado'}
# )

# ax.set_title('Grid completo + Município + Células utilizadas')
# ax.legend()

# plt.show()


# # =============================================================================
# # PLOT 2 - APENAS MUNICÍPIO E CÉLULAS UTILIZADAS
# # =============================================================================

# fig, ax = plt.subplots(figsize=(12, 12))

# mun.plot(
#     ax=ax,
#     facecolor='none',
#     edgecolor='black',
#     linewidth=2
# )

# cells_plot.plot(
#     ax=ax,
#     facecolor='red',
#     edgecolor='black',
#     alpha=0.5
# )

# ax.set_title('Células utilizadas pela desagregação')

# plt.show()


# # =============================================================================
# # PLOT 3 - MUNICÍPIO + IDs DAS CÉLULAS
# # =============================================================================

# fig, ax = plt.subplots(figsize=(12, 12))

# mun.plot(
#     ax=ax,
#     facecolor='none',
#     edgecolor='black',
#     linewidth=2
# )

# cells_plot.plot(
#     ax=ax,
#     facecolor='red',
#     edgecolor='black',
#     alpha=0.5
# )

# for _, row in cells_plot.iterrows():
#     centroid = row.geometry.centroid
#     ax.text(
#         centroid.x,
#         centroid.y,
#         str(int(row['fid'])),
#         fontsize=8,
#         ha='center',
#         va='center'
#     )

# ax.set_title('FIDs utilizados pela desagregação')

# plt.show()


# # =============================================================================
# # PLOT 4 - ZOOM AUTOMÁTICO NO MUNICÍPIO
# # =============================================================================

# fig, ax = plt.subplots(figsize=(12, 12))

# shp_cells.boundary.plot(
#     ax=ax,
#     color='lightgray',
#     linewidth=0.5
# )

# mun.plot(
#     ax=ax,
#     facecolor='none',
#     edgecolor='black',
#     linewidth=2
# )

# cells_plot.plot(
#     ax=ax,
#     facecolor='red',
#     edgecolor='black',
#     alpha=0.7
# )

# xmin, ymin, xmax, ymax = mun.total_bounds

# dx = (xmax - xmin) * 0.10
# dy = (ymax - ymin) * 0.10

# ax.set_xlim(xmin - dx, xmax + dx)
# ax.set_ylim(ymin - dy, ymax + dy)

# ax.set_title('Zoom no município')

# plt.show()


# # =============================================================================
# # TABELA RESUMO
# # =============================================================================

# resumo = (
#     cells_plot[['fid', 'vkt_fraction']]
#     .sort_values('vkt_fraction', ascending=False)
#     .reset_index(drop=True)
# )

# print('\nResumo das células utilizadas:')
# print(resumo)

# print('\nSoma total do VKT fraction:')
# print(resumo['vkt_fraction'].sum())

#%%

# Main function for emission calculations for each city
def processar_combustivel(desg_consumo_city, temp_hour, cidade, mes, comb, props,
                          volume_mensal, ethanolPerc, EFCarRefueling_hour, 
                          rvpCurve , EFSubmergedFilling ,EFTankBreathing , voc_density_comb):
    """
    Calculates hourly evaporative VOC emissions according
    to city and fuel.

    Parameters
    ----------
    desg_consumo_city : pandas.DataFrame
        Hourly consumption disaggregated by cell.
    temp_hour : pandas.DataFrame
        Hourly temperature of the city.
    cidade : int
        IBGE municipality code.
    mes : int
        Analyzed month.
    comb : str
        Fuel type.
    props : dict
        Fuel properties.
    volume_mensal : float
        Monthly consumed volume (L).
    ethanolPerc : float
        Ethanol percentage.
    EFCarRefueling_hour : numpy.ndarray
        Hourly refueling emission factors.
    rvpCurve : pandas.DataFrame
        RVP curve.
    EFSubmergedFilling : float
        Emission factor for submerged filling.
    EFTankBreathing : float
        Tank breathing emission factor.
    voc_density_comb : pandas.DataFrame
        VOC density by temperature.

    Returns
    -------
    pandas.DataFrame
        Hourly emissions per cell and municipality in g/hour and L/hour
    """
    
    # ethanolPerc = props["ethanolPerc"]
    # Fuel consumption per hour according to VKT
    desg_consumo_city["cons_hour"] = float(volume_mensal) * desg_consumo_city["vkt_fraction_corrigido"]

    desg_consumo_city_m = desg_consumo_city.reset_index().rename(columns={"date_range": "datetime"})
    
    # Merge with temperature data
    desg_consumo_city_m = desg_consumo_city_m.merge(temp_hour[["datetime", "TEMP_C"]], on="datetime", how="left")
    desg_consumo_city_m.loc[desg_consumo_city_m['TEMP_C'].isna(), 'TEMP_C'] = desg_consumo_city_m['TEMP_C'].mean()

    # Base dataframe creation
    df_ef = pd.DataFrame({
        "datetime": pd.to_datetime(temp_hour["datetime"]),
        "EF reabastecimento": EFCarRefueling_hour,
    })
    
    # Merge with refueling emission factors
    desg_consumo_city_m = desg_consumo_city_m.merge(df_ef, on="datetime", how="left")
    desg_consumo_city_m["datetime"] =  pd.to_datetime(desg_consumo_city_m["datetime"])
    desg_consumo_city_m = desg_consumo_city_m.set_index('datetime')

    # Tank breathing emissions
    desg_consumo_city_m["emis_total"] = desg_consumo_city_m["cons_hour"] * EFTankBreathing
    
    # Refueling emissions during commercial hours (5:00 - 22:00)
    mask_horas = (desg_consumo_city_m.index.hour >= 5) & (desg_consumo_city_m.index.hour <= 23)
    desg_consumo_city_m.loc[mask_horas, "emis_total"] += (
    desg_consumo_city_m.loc[mask_horas, "cons_hour"].fillna(0)
    * desg_consumo_city_m.loc[mask_horas, "EF reabastecimento"].fillna(0))

    # Submerged Filling
    # Calculating weekly fuel consumption
    desg_consumo_city_m["semana"] = desg_consumo_city_m.index.to_period("W")
    desg_consumo_city_m["consumo_semanal"] = (
        desg_consumo_city_m.groupby(["cell_id", "semana"])["cons_hour"].transform("sum"))
    
    # Generating fuel dumping days in the tank
    dias_semana_submerged = np.random.choice(range(7), size=3, replace=False)
    horas_submerged = [np.random.randint(6, 23) for _ in range(3)]
    eventos_submerged = list(zip(dias_semana_submerged, horas_submerged))
    mask_submerged = desg_consumo_city_m.index.to_series().apply(
        lambda dt: (dt.weekday(), dt.hour) in eventos_submerged)
    
    # Calculating emissions from fuel dumping in the tank
    desg_consumo_city_m["emis_submerged"] = 0.0
    desg_consumo_city_m.loc[mask_submerged, "emis_submerged"] = (
        desg_consumo_city_m.loc[mask_submerged, "consumo_semanal"] * EFSubmergedFilling / 3)

    # Adding dumping emissions to total emissions
    desg_consumo_city_m = desg_consumo_city_m.reset_index()
    desg_consumo_city_m["emis_total"] += desg_consumo_city_m["emis_submerged"]
    
    ### CONVERSION mg/h ---> g/h
    desg_consumo_city_m["emis_total"] = desg_consumo_city_m["emis_total"]/1000
    
    # Merge with hourly temperatures and VOC density
    desg_consumo_city_m['TEMP_C'] = desg_consumo_city_m['TEMP_C'].round().astype(int)
    desg_consumo_city_m = desg_consumo_city_m.merge(voc_density_comb,
                            left_on='TEMP_C',
                            right_on = 'temp_C',
                            how='left')
 
    # Calculation of evaporated VOC volume
    desg_consumo_city_m['emis_total_litros'] = desg_consumo_city_m['emis_total'] / desg_consumo_city_m[voc_density_comb.columns[0]]
   
    # Rename columns
    desg_consumo_city_m.rename(columns={
        'emis_total': f'VOC_{comb}_{ethanolPerc}_Porc(g)',
        'emis_total_litros': f'VOC_{comb}_{ethanolPerc}_Porc(L)'},inplace=True)
    
    return desg_consumo_city_m[["datetime","city_id" ,"cell_id", f'VOC_{comb}_{ethanolPerc}_Porc(g)',f'VOC_{comb}_{ethanolPerc}_Porc(L)']]
