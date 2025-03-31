import requests
import json
import time
from superlogica_chamadas_API.preparo_condominio import PreparoCondominio
from rammer_utils.utils.email import enviar_email, criar_email
from rammer_utils.utils.log import init_root_logger
import logging
from datetime import datetime, timedelta

init_root_logger()
logger = logging.getLogger(__name__)

get_header = {
    'Content-Type': 'application/json',
    'app_token' : 'abcaac41-b011-4dad-bf94-d078eb4e3cc2',
    'access_token' : '10c4f4d3-894b-480b-a84e-fade81415b7c'    
}

def get_id_sl(codigo: int):
    # pegando todos os ids
    dic = {}
    PreparoCondominio.construir_de_para_base_sl(dic)
    # dic['1160']
    return int(dic[str(codigo)])

import requests


def get_all_condominios():

    condominios = []
    page = 1
    while True:
        url = f'https://api.superlogica.net/v2/condor/condominios/get?id=-1&somenteCondominiosAtivos=1&ignorarCondominioModelo=1&apenasColunasPrincipais=1&apenasDadosDoPlanoDeContas=0&comDataFechamento=1&itensPorPagina=50&pagina={page}'
        response = requests.get(
                url=url,
                headers=get_header
            )
            
        if response.status_code != 200:
            print(f"Erro ao acessar a API: {response.status_code}")
            break
        
        data = response.json()
        
        for condominio in data:
            
            condominios.append(condominio)
        
        if len(data) < 50:
            break  # Para o loop quando o número de unidades retornadas for menor que 50
        
        page += 1

    return condominios

def get_unidades(id_sl: int):
    unidades = []
    page = 1
    while True:
        url = f'https://api.superlogica.net/v2/condor/unidades/index?idCondominio={id_sl}&exibirGruposDasUnidades=1&itensPorPagina=50&pagina={page}&exibirDadosDosContatos=1'
        response = requests.get(
            url=url,
            headers=get_header
        )
        
        if response.status_code != 200:
            print(f"Erro ao acessar a API: {response.status_code}")
            break
        
        data = response.json()
        
        unidades.extend(data)
        
        if len(data) < 50:
            break  # Para o loop quando o número de unidades retornadas for menor que 50
        
        page += 1
    
    return unidades



def search_id_unidades(unidades: list):

    ids_unidades = []
    for unidade in unidades:
        ids_unidades.append((unidade['st_unidade_uni'], unidade['id_unidade_uni']))
    
    return ids_unidades

import requests

def get_cobrancas_de_unidade(id_unidades: list, id_sl:int):
    cobrancas = {}

    opcoes_de_status = ['pendentes']
    for id_unidade in id_unidades:
        cobrancas_por_status = {}

        for opcao_de_status in opcoes_de_status:
            url = f'https://api.superlogica.net/v2/condor/cobranca/index?status={opcao_de_status}&apenasColunasPrincipais=1&exibirPgtoComDiferenca=1&comContatosDaUnidade=1&idCondominio={id_sl}&dtInicio=03/01/2025&dtFim=03/31/2025&UNIDADES[0]={id_unidade[1]}&itensPorPagina=50&pagina=1'
            time.sleep(1.5)
            response = requests.get(url, headers=get_header)

            if response.status_code != 200:
                print(f"Erro ao acessar a API para unidade {id_unidade}: {response.status_code}, {opcao_de_status}")
                continue  # Continua para o próximo status
            
            data = response.json()
            cobrancas_por_status[opcao_de_status] = data  # Associa corretamente cada status aos seus dados

        cobrancas[id_unidade] = cobrancas_por_status  # Associa os dados ao ID da unidade
    
    return cobrancas

def enviar_dados_por_email(lista_resultados, destinatarios):

    corpo = """
    <html>
        <body>
            <h2>Resultados:</h2>
            <ul>
    """

    for resultado in lista_resultados:
        corpo += "<li><strong>" + "</strong><br>".join([f"{k}: {v}" for k, v in resultado.items()]) + "</li><br><br>"

    corpo += """
            </ul>
        </body>
    </html>
    """
    mail = criar_email(
            assunto='Teste - Cobranças Sem confirmação',
            corpo= corpo,
            destinatarios =destinatarios
        )
    
    enviar_mail = enviar_email(mail)

def extrair_e_salvar(dados, condominio, nome_arquivo="resultado.txt"):
    with open(nome_arquivo, "a", encoding="utf-8") as f:  # Modo 'a' para adicionar sem sobrescrever
        # Para cada item nos dados, que é uma tupla com (chave_tupla, valor_dict)

        # Desempacota a tupla
        chave_tupla = dados[0]
        valor_dict = dados[1]
                
        # Extrai os componentes da chave
        st_unidade_uni = chave_tupla[0]  # 'AP 0002'
        id_unidade_uni = chave_tupla[1]  # '63'
        
        # Verifica se existe a chave 'pendentes' e se ela contém itens
        if 'pendentes' in valor_dict and valor_dict['pendentes']:
            for pendente in valor_dict['pendentes']:  # Itera sobre os dicionários na lista de pendentes
                
                
                if pendente.get("fl_remessastatus_recb") == '2' or pendente.get("fl_remessastatus_recb") == '0' or pendente.get("fl_remessastatus_recb") == '-1'  :
                    # Cria um dicionário com as informações relevantes
                    resultado = {
                        "condominio" : condominio,
                        "unidade": st_unidade_uni,
                        "id_unidade": id_unidade_uni,
                        "fl_status_recb": pendente.get("fl_status_recb", "N/A"),
                        "fl_remessastatus_recb": pendente.get("fl_remessastatus_recb", "N/A"),
                        "id_recebimento_recb": pendente.get("id_recebimento_recb", "N/A"),
                        "st_documento_recb": pendente.get("st_documento_recb", "N/A"),
                        "dt_vencimento_recb": pendente.get("dt_vencimento_recb", "N/A"),
                        "vl_total_recb": pendente.get("vl_total_recb", "N/A")
                    }

                    # Escrevendo no arquivo
                    f.write("\n".join([f"{k}: {v}" for k, v in resultado.items()]) + "\n\n")
                    return resultado
                else:
                    return False

def main():
    logger.info("Estou começando")
    lista_de_cobrança_para_email = []
    destinatarios = [
        'rafael.moreno@estasa.com.br',
        'jonathan.mendes@estasa.com.br'
    ]
    condominios = get_all_condominios()
    cond_com_boletos_stt_2 = set() 
    for condominio in condominios:
        logger.info(f"Estou passando pelo condominio : {condominio.get('st_label_cond')}")
        id_sl = condominio.get('id_condominio_cond')
        
        unidades = get_unidades(id_sl)
        
        id_unidades = search_id_unidades(unidades)
        
        cobrancas_de_unidades = get_cobrancas_de_unidade(id_unidades, id_sl)
        
        for cobranca in cobrancas_de_unidades.items():
            resultado = extrair_e_salvar(cobranca, condominio.get('st_label_cond'))
            if resultado:
                lista_de_cobrança_para_email.append(resultado)
                cond_com_boletos_stt_2.add(condominio.get('st_label_cond'))

        logger.info(f"Estou Acabei de passsar o condominio, indo para o proximo")
    logger.info("estou enviando o email")
    enviar_dados_por_email(lista_de_cobrança_para_email, destinatarios)
main()