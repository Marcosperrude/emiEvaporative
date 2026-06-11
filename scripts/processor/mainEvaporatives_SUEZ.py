# %%
import geopandas as gpd
import pandas as pd
import os
import xarray as xr
from tqdm import tqdm   # barra de progresso
import matplotlib.pyplot as plt
import numpy as np 
from functionsEmissionFactors import carRefuelingEF, rvp
from functionsEmissions import carregar_vkt_city, processar_combustivel, filtragempostos , filtragemcelulas
# =============================================================================
# import warnings
# =============================================================================

from multiprocessing import Pool
from functools import partial

np.random.seed(42)

# %%
############### VARIAVEIS
# Caminho geral
tablePath = os.path.dirname(os.path.dirname(os.path.dirname(os.getcwd())))

# Caminhos das pastas
dataPath = tablePath + '/inputs'
outPath = tablePath + "/outputs"
outPathInter = tablePath + "/outputs_intermediarios"

# Pasto com os outputs das emissoes/cidade
emiPathCity = outPath + "/emissoes_cidades"

# Pasta com outputs agrupados por dia pro Brasil
emiPathBrasil = outPath + "/emissoes_brasil"

# Shapefile municípios do brasil
br_municipios = dataPath + '/BR_Municipios_2022/BR_Municipios_2022.shp'

# Densidade de VOC de acordo com a tempratura
voc_density = dataPath + "/VOC_density.csv"

# Curva de pressão de vapor da combustivel em relação a % de etanol
# Extrai os dados de RVP do gráfico do artigo
# https://d35t1syewk4d42.cloudfront.net/file/1410/RVP-Effects-Memo_03_26_12_Final.pdf
rvp_curve = dataPath + "/RVP.csv"

# Pasta com os VKT horario por cada cidade para a desagregação de consumo de combsutivel
desagPath = dataPath + '/desagregacao_vkt'

# Grid de localização MCIP
grid = dataPath + '/mesh_12km.gpkg'

# CSV com postos do brasil cadastrados no banco de dados do IBAMA
dados_ibama  = dataPath + '/postos.csv'

# CSV com postos do brasil cadastrados no banco de dados do Agencia Nacional de Petróleo (anp)
dados_anp = dataPath + '/dados-cadastrais-revendedores-varejistas-combustiveis-automoveis.csv'

# Pasta com as temperatura media horária de cada cidade (obtivo pelo codigo AnalysisTemp)
tempPath = outPathInter +'/temperatura_csv'

# XLSX com proporção de consumo de combustivel para o uso em transportes (BEN)
# DADO PELO BRAVES CLASSIC
desag_ben = dataPath + '/ConsumoCombustiveTransporte_BEN.xlsx'

# XLSX de movimentação de combustível no Brasil por cidade e mês em m³
consumo_comb = dataPath + "/SIC 48003009498202458_2006-a-2023.xlsx"

# Parãmetros de analise:
    # ethanolPerc : Porcentagem de Etanol no combustível
    # voc_density : Densidade do VOC de acordo com o tipo de combustível
    # desag : Proporçao do consumo de combustivel de acordo com o BEN
combustiveis = {
    "GASOLINA C": {"ethanolPerc": 27,
                   'voc_density': 'VOC_gaso_dens',
                   'desag' : "Porcentagem Gasolina"},
    "AEHC": {"ethanolPerc": 93,
             'voc_density': 'VOC_eth_dens',
             'desag' : "Porcentagem Etanol"}
}

# Análise das cidades sem o combustivel analisado
cidades_sem_combustivel = []

# Análise das cidades sem VKT (Cidades sem postos cadastrados no IBAMA)
cidades_sem_vkt = []

# Número de processadores
n_processors = 1

# Periodo a ser analisado
anos = [2023]
meses = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

# %%
################### CARREGAMENTO

# SHP Brasil municípios
shp_mun = gpd.read_file(br_municipios).to_crs("EPSG:4326")
shp_mun['CD_MUN'] = shp_mun['CD_MUN'].astype(int)

# Densidade VOC 
voc_density = pd.read_csv(voc_density)
# Conversão de Kg/L para g/L
voc_density[['VOC_gaso_dens', 'VOC_eth_dens']] = voc_density[
    ['VOC_gaso_dens', 'VOC_eth_dens']]  * 1000

# Curva RVP
rvpCurve = pd.read_csv(rvp_curve)

# Celulas de localização (id_cell)
shp_cells = gpd.read_file(grid)
shp_cells['fid'] = shp_cells.index

# Postos IBAMA
postos_ibama = pd.read_csv(dados_ibama)

# Postos ANP
postos_anp = pd.read_csv(dados_anp, sep=';')

# Proporção de consumo BEN
ConBen = pd.read_excel(desag_ben)

#%%
import warnings

def process_city(mun_grid, temp, postos_ibama, postos_anp, desg_consumo, 
                 shp_cells, combustiveis, voc_density, ConBen, ano, mes, shp_mun, 
                 grid_nome):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        
        mes_num = int(str(mes)[-2:])
        resultado_final = []
       
        for i in mun_grid:
            # i = 3550308
            try:
                mun = shp_mun[shp_mun['CD_MUN'] == i]
                df_temp_city = temp[temp["CD_MUN"] == i].sort_values("datetime")
                
                # postos_anp_loc = filtragempostos(postos_anp, postos_ibama)
                # gdf = gpd.GeoDataFrame(postos_anp_loc,
                #     geometry=gpd.points_from_xy(postos_anp_loc["Longitude"], postos_anp_loc["Latitude"]),
                #     crs=shp_cells.crs)
                # mun_postos = gpd.sjoin(gdf, mun, how='inner', predicate='within')
                # mun_postos = mun_postos.drop(columns=['index_right'], errors='ignore')
                
                desg_consumo_city,prop = carregar_vkt_city(postos_ibama,postos_anp,
                                                       desg_consumo,i, shp_cells,mun)
                
                # grid_postos = gpd.sjoin(mun_postos, shp_cells, how='inner', predicate='within')
                
                if desg_consumo_city.empty:
                    continue

                temp_hour = df_temp_city[df_temp_city["month"] == mes_num].reset_index()
                resultados = []
                for comb, props in combustiveis.items():
                    try:

                        volume_mensal = float( sheet_volume.loc[(
                            (sheet_volume["COD_LOCALIDADE_IBGE_D"] == i) &
                            (sheet_volume["NOM_GRUPO_PRODUTO"] == comb)
                        ), mes].iloc[0]) * 1000
                        volume_mensal = volume_mensal * prop
        
                            
                        volume_mensal = volume_mensal * ConBen.loc[ConBen[
                            'Ano'] == ano, props['desag'] ].iloc[0]


                        voc_density_comb = voc_density[[props["voc_density"], 'temp_C']]
                        EFCarRefueling_hour = carRefuelingEF(temp_hour["TEMP_C"].values, props["ethanolPerc"], rvpCurve)
                        EFSubmergedFilling = rvp(props["ethanolPerc"], 880, rvpCurve)
                        EFTankBreathing = rvp(props["ethanolPerc"], 120, rvpCurve)
                        df_comb = processar_combustivel(desg_consumo_city, temp_hour, 
                                                        i, mes, comb, props, volume_mensal, 
                                                        props["ethanolPerc"], EFCarRefueling_hour,
                                                        rvpCurve, EFSubmergedFilling, 
                                                        EFTankBreathing, voc_density_comb)
                        df_comb['datetime'] = df_comb['datetime'] + pd.Timedelta(hours=3)
                        df_comb = df_comb.dropna(
                            subset=[f'VOC_{comb}_{props["ethanolPerc"]}_Porc(g)'],
                            how='all')
                        data_to_concat = []
                        for cell_id in df_comb['cell_id'].unique():
                            
                            emiss_cell = df_comb[df_comb['cell_id'] == cell_id].copy()
                            emiss_cell = emiss_cell.sort_values(['cell_id','datetime']).reset_index(drop=True)
                            primeira_hora = emiss_cell.loc[emiss_cell['datetime'].dt.hour == 3].iloc[[0]].copy()
                            hora_2 = primeira_hora.copy()
                            hora_2['datetime'] = hora_2['datetime'] - pd.Timedelta(hours=1)
                            hora_1 = primeira_hora.copy()
                            hora_1['datetime'] = hora_1['datetime'] - pd.Timedelta(hours=2)
                            hora_0 = primeira_hora.copy()
                            hora_0['datetime'] = hora_0['datetime'] - pd.Timedelta(hours=3)
                            data_to_concat.append(hora_0)
                            data_to_concat.append(hora_1)
                            data_to_concat.append(hora_2)
                            data_to_concat.append(emiss_cell)
                        df_comb = pd.concat(data_to_concat, ignore_index=True)
                        df_comb = df_comb.sort_values(['cell_id','datetime']).reset_index(drop=True)
                        resultados.append(df_comb)
                    except Exception as e:
                        print(f'Erro cidade={i}, combustivel={comb}: {e}')
                        continue

                if len(resultados) == 0:
                    continue

                emissoes_cidade = pd.concat(resultados, ignore_index=True)
                emissoes_cidade = emissoes_cidade.groupby(['city_id', 'cell_id', 'datetime'],
                        as_index=False).sum(numeric_only=True)
                resultado_final.append(emissoes_cidade)

            except Exception as e:
                print(f'Erro município={i}: {e}')
                continue

        if len(resultado_final) == 0:
            print(f'Nenhum resultado para {grid_nome}')
            return

        emissoes_grid = pd.concat(resultado_final, ignore_index=True)
        emissoes_grid = emissoes_grid.drop(columns=['city_id'], errors='ignore').groupby(
            ["cell_id", "datetime"], as_index=False).sum(numeric_only=True)

      
        filename_parquet = f"{outPath}/Suez/{grid_nome}/emissoes_{ano}_{str(mes_num).zfill(2)}/{grid_nome}_{ano}_{str(mes_num).zfill(2)}.parquet"

        os.makedirs(os.path.dirname(filename_parquet), exist_ok=True)

        emissoes_grid.to_parquet(filename_parquet, index=False)

        print(f'GRID {grid_nome} salvo - {ano}-{mes_num:02d}')

grids_suez = ['CAMPINA_GRANDE','CAMPO_GRANDE','CORUMBA','MANAUS','PORTO_ALEGRE','SAO_PAULO']
shp = {
'CAMPINA_GRANDE': "CGR_500M",
'CAMPO_GRANDE': "CPG_500M",
'CORUMBA': "COR_500M",
'MANAUS': "MAO_500M",
'PORTO_ALEGRE': "POA_500M",
'SAO_PAULO': "SP_500M"}
for ano in anos:
    # ano = 2023
    sheet_volume = pd.read_excel(consumo_comb, skiprows=4, sheet_name=f'{ano}')
    colunas_meses = [c for c in sheet_volume.columns if str(c).startswith("20")]
    for mes in colunas_meses:
        # mes= 202312

        mes_num = int(str(mes)[-2:])
        if mes_num not in meses:
            continue

        temp = pd.read_csv(tempPath + f"/temperatura_cidade_{ano}_{mes_num:02d}.csv")
        temp["datetime"] = pd.to_datetime(temp[["year", "month", "day", "hour"]])
        temp = temp.set_index("datetime")

        for grid_nome in grids_suez:
            # grid_nome ='CORUMBA'
            
            
            mes_num = int(str(mes)[-2:])
            shp_grid = shp[grid_nome]
            
            print(f'Processando {grid_nome} - {ano}-{mes_num:02d}')
            
            shp_cells = gpd.read_file(
               os.path.join(dataPath, 'SUEZ_ref2023', grid_nome,
                            f'GRIDDOT2D_{grid_nome}_500m_2023-01-01.gpkg')).to_crs("EPSG:4326")
            
            shp_cells['fid'] = shp_cells.index

            mun_grid = gpd.sjoin(shp_cells,shp_mun[['CD_MUN','geometry']],
                    how='inner',predicate='intersects')['CD_MUN'].astype(int).unique()

            pasta_vkt = os.path.join(desagPath, 'SUEZ_ref2023', grid_nome)
            arquivos_parquet = [os.path.join(pasta_vkt, f)for f in os.listdir(pasta_vkt)
                if f.startswith(f"{ano}-{mes_num:02d}") and f.endswith(".parquet")]

            desg_consumo = pd.concat((pd.read_parquet(f) for f in arquivos_parquet)).reset_index()
            process_city(mun_grid, temp, postos_ibama, postos_anp,
                         desg_consumo, shp_cells, combustiveis, voc_density, 
                         ConBen, ano, mes, shp_mun, grid_nome)
#%%
for ano in anos:
    for mes in meses:

        mes = f'{mes:02}'
        for grid_nome in grids_suez:

            emiPath = os.path.join(outPath, "Suez", grid_nome, f"emissoes_{ano}_{mes}")
            nome_arquivo_grid = os.path.join(emiPath, f"{grid_nome}_{ano}_{mes}.parquet")

            if not os.path.exists(nome_arquivo_grid):
                print(f'Arquivo não encontrado: {nome_arquivo_grid}')
                continue

            emissoes = pd.read_parquet(nome_arquivo_grid)

            emissoes['datetime'] = pd.to_datetime(emissoes['datetime'])
            emissoes = emissoes[emissoes['datetime'].dt.month == int(mes)]

            for dia in sorted(emissoes['datetime'].dt.day.unique()):

                emissoes_dia = emissoes[emissoes['datetime'].dt.day == dia]

                emissoes_dia = emissoes_dia.groupby(["datetime","cell_id"], as_index=False).sum(numeric_only=True)

                os.makedirs(os.path.join(outPath, 'Suez',grid_nome, f"agregado_emissoes_{ano}"), exist_ok=True)

                nome_arquivo = os.path.join(outPath,'Suez', grid_nome, f"agregado_emissoes_{ano}", f"{grid_nome}_{ano}-{mes}-{dia:02}.parquet")
                emissoes_dia.to_parquet(nome_arquivo, index=False)
                print(f"{grid_nome} - dia {dia:02}-{mes}-{ano} salvo")