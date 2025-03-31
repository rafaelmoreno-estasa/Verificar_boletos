import requests
import json
import time
from superlogica_chamadas_API.preparo_condominio import PreparoCondominio
from rammer_utils.utils.email import enviar_email, criar_email
from rammer_utils.utils.log import init_root_logger
from rammer_utils.utils.config import Config
import logging
from tqdm import tqdm
import re
from datetime import datetime, timedelta
init_root_logger()
logger = logging.getLogger(__name__)

get_header = {
    'Content-Type': 'application/json',
    'app_token': 'abcaac41-b011-4dad-bf94-d078eb4e3cc2',
    'access_token': '10c4f4d3-894b-480b-a84e-fade81415b7c'    
}


def ler_configuracao(caminho_arquivo="configuracao.json", ambiente="[GERAL]"):
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
            configuracao = json.load(arquivo)
        
        # Retorna as configurações do ambiente desejado, ou um dicionário vazio se não existir
        return configuracao.get(ambiente, {})
    
    except FileNotFoundError:
        print(f"Erro: O arquivo {caminho_arquivo} não foi encontrado.")
    except json.JSONDecodeError:
        print(f"Erro: O arquivo {caminho_arquivo} contém um JSON inválido.")
    
    return None

def get_all_condominios():
    condominios = []
    page = 1

    logger.info("Iniciando busca de todos os condomínios")

    while True:
        url = f'https://api.superlogica.net/v2/condor/condominios/get?id=-1&somenteCondominiosAtivos=1&ignorarCondominioModelo=1&apenasColunasPrincipais=1&apenasDadosDoPlanoDeContas=0&comDataFechamento=1&itensPorPagina=50&pagina={page}'
        response = requests.get(url, headers=get_header)

        if response.status_code != 200:
            logger.error(f"Erro ao acessar a API: {response.status_code}")
            break

        data = response.json()
        condominios.extend(data)

        logger.info(f"Página {page} processada. {len(data)} condomínios encontrados.")

        if len(data) < 50:
            break

        page += 1

    logger.info(f"Busca de condomínios concluída. Total de {len(condominios)} condomínios.")
    return condominios

def tem_final_rem(texto: str) -> bool:
    return bool(re.search(r"\.rem$", texto))

def verificar_documentos_de_um_condominio(id_sl):
    page = 1
    info_documentos_cond = []

#    logger.info(f"Verificando documentos para o condomínio ID: {id_sl}")

    while True:
        url = f'https://api.superlogica.net/v2/condor/impressoes/index?idCondominio={id_sl}&publicadoApenasPara=administracao&dtInicio=03/01/2025&dtFim=03/31/2025&itensPorPagina=50&pagina={page}&comStatus=atuais'
        response = requests.get(url, headers=get_header)

        if response.status_code != 200:
            logger.error(f"Erro ao acessar a API para condomínio {id_sl}: {response.status_code}")
            break

        data = response.json()

        hoje = datetime.today().date()  
        cinco_dias_atras = hoje - timedelta(days=5) 
        for documento in data:
            data_criacao_str = documento.get('dt_criacao_fimp', '')

            try:
                data_criacao = datetime.strptime(data_criacao_str, "%m/%d/%Y %H:%M:%S").date()
                
                if tem_final_rem(documento.get("st_arquivo_fimp", "")) and cinco_dias_atras <= data_criacao <= hoje:
                    info_documentos_cond.append({
                        "filename": documento.get('st_descricao_fimp'),
                        "id_impressao_fimp": documento.get('id_impressao_fimp'),
                        "dt_criacao_fimp": data_criacao_str
                    })
            
            except ValueError:
                continue

        if len(data) < 50:
            break

        page += 1


    return info_documentos_cond

def extrair_enderecos(caminho_arquivo):
    enderecos = []
    
    with open(caminho_arquivo, 'r') as arquivo:
        for linha in arquivo:
            if linha[13] == 'Q': 
                endereco = linha[72:102].strip()
                bairro = linha[102:117].strip()
                cep = linha[117:125].strip()
                cidade = linha[125:150].strip()
                uf = linha[150:152].strip()
                enderecos.append({
                    'endereco' : endereco,
                    'bairro' : bairro,
                    'cep' : cep,
                    'cidade' : cidade,
                    'uf' : uf
                })
    
    return enderecos


def processar_doc_cobranca(documento):

    for doc in documento:
        try:
            filename = doc.get('filename')
            id_impressao_fimp = doc.get('id_impressao_fimp')
            dt_criacao_fimp = doc.get('dt_criacao_fimp')

            response = requests.get(url = f'https://api.superlogica.net/v2/condor/documentos/download?id={id_impressao_fimp}', headers= get_header)


            txt_de_unidades_da_remassa = response.content
            
            try:
                with open('documento_temporario.txt', 'wb') as f:
                    f.write(response.content)

                enderecos = extrair_enderecos('documento_temporario.txt')

                return enderecos
            except:
                pass
        except:
            pass



def get_codigo_from_enderecos(enderecos):
    ids_sl = set()  # Usando um set para evitar duplicados

    for endereco in enderecos:
        response = requests.get(f"https://servidor-webapp.estasa.net:8085/apisqlserver/get_condominio_by_address?endereco={endereco.get('endereco')}", verify=False)

        if response.status_code == 200:
            all_adress = response.json()
            if all_adress:
                codigo = all_adress.get('codigo')
                if codigo:
                    ids_sl.add(codigo)  # Adiciona no set

    return list(ids_sl)  # Converte para lista no retorno

def get_unidades(id_sl):
    unidades = []
    page = 1
    while True:
        url = f'https://api.superlogica.net/v2/condor/unidades/index?idCondominio={id_sl}&exibirGruposDasUnidades=1&itensPorPagina=50&pagina={page}&exibirDadosDosContatos=1'
        time.sleep(1.5)
        response = requests.get(url, headers=get_header)
        if response.status_code != 200:
            logger.error(f"Erro ao acessar a API: {response.status_code}")
            break

        data = response.json()
        unidades.extend(data)

        if len(data) < 50:
            break
        page += 1

    return unidades

def search_id_unidades(unidades):
    return [(unidade['st_unidade_uni'], unidade['id_unidade_uni']) for unidade in unidades]


def get_cobrancas_de_unidade(id_unidade, id_sl):
    # Obtém o primeiro dia do mês atual
    hoje = datetime.today()
    primeiro_dia = hoje.replace(day=1).strftime("%m/01/%Y")
    
    # Calcula o último dia do mês atual
    proximo_mes = hoje.replace(day=28) + timedelta(days=4)  # Garante que ultrapassamos o último dia do mês
    ultimo_dia = proximo_mes.replace(day=1) - timedelta(days=1)
    ultimo_dia_str = ultimo_dia.strftime("%m/%d/%Y")

    url = (f'https://api.superlogica.net/v2/condor/cobranca/index?status=pendentes'
            f'&apenasColunasPrincipais=1&exibirPgtoComDiferenca=1&comContatosDaUnidade=1'
            f'&idCondominio={id_sl}&dtInicio={primeiro_dia}&dtFim={ultimo_dia_str}'
            f'&UNIDADES[0]={id_unidade}&itensPorPagina=50&pagina=1')

    response = requests.get(url, headers=get_header)
    time.sleep(1.5)  # Respeitar limite de requisição da API

    if response.status_code != 200:
        logger.error(f"Erro ao acessar a API para unidade {id_unidade}: {response.status_code}")
        return []

    return response.json()


def processar_cobrancas(cobrancas, condominio, unidade):
    for pendente in cobrancas:
        status = pendente.get("fl_remessastatus_recb")
        if status in ['2', '0']:
            return {
                "condominio": condominio,
                "unidade": unidade[0],
                "id_unidade": unidade[1],
                "fl_status_recb": pendente.get("fl_status_recb", "N/A"),
                "fl_remessastatus_recb": status,
                "id_recebimento_recb": pendente.get("id_recebimento_recb", "N/A"),
                "st_documento_recb": pendente.get("st_documento_recb", "N/A"),
                "dt_vencimento_recb": pendente.get("dt_vencimento_recb", "N/A"),
                "vl_total_recb": pendente.get("vl_total_recb", "N/A")
            }
    return None

def enviar_dados_por_email(lista_resultados, destinatarios, copiados):
    corpo = """
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                h2 { color: #2c3e50; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #2c3e50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <h2>Resultados:</h2>
            <table>
                <tr>
                    <th>Condominio</th>
                    <th>Data de Vencimento</th>
                    <th>ID da cobrança</th>
                </tr>
    """
    
    for resultado in lista_resultados:
        condominio = resultado.get("condominio", "N/A")
        dt_vencimento_str = resultado.get("dt_vencimento_recb", "N/A")
        dt_vencimento = dt_vencimento_str.split()[0]
        dt_vencimento = datetime.strptime(dt_vencimento, "%m/%d/%Y").strftime("%d/%m/%Y")
        id_recebimento_recb = resultado.get('id_recebimento_recb', "N/A")
        corpo += f"""
                <tr>
                    <td>{condominio}</td>
                    <td>{dt_vencimento}</td>
                    <td>{id_recebimento_recb}</td>
                </tr>
        """

    corpo += """
            </table>
        </body>
    </html>
    """
    
    corpo += """</ul></body></html>"""
    mail = criar_email(assunto='Cobranças Sem Confirmação do Banco', corpo=corpo, destinatarios=destinatarios, copiados=copiados)
    enviar_email(mail)
    return True

def main():
    conds = get_all_condominios()
    
    
    info_documentos_de_cobranca = []

    logger.info("Iniciando a verificação de documentos para todos os condomínios")

    for cond in tqdm(conds, desc="Verificando condomínios"):
        documentos = verificar_documentos_de_um_condominio(cond.get("id_condominio_cond"))
    
    
        if documentos:
            info_documentos_de_cobranca.append(documentos)

    dic_lista_de_endereco = []

    for doc in tqdm(info_documentos_de_cobranca, desc="verificao de informação de doc"):
        doc_de_cobranca_processado = processar_doc_cobranca(doc)
        if doc_de_cobranca_processado:
            for endereco in doc_de_cobranca_processado:
                dic_lista_de_endereco.append(endereco)


    codigos = get_codigo_from_enderecos(dic_lista_de_endereco)

    tuplas_codigo_id = []
    for codigo in codigos:
        for cond in conds:
            if str(codigo) == cond.get('st_label_cond'):
                tuplas_codigo_id.append((codigo ,cond.get('id_condominio_cond')))

    lista_de_cobranca_para_email = []
    
    config = ler_configuracao()
    destinatarios = config.get('destinatarios')
    copiados = config.get('copiados')

    for id_sl in tqdm(tuplas_codigo_id, desc="Verificando as cobranças de cada condomino"):
        unidades = search_id_unidades(get_unidades(id_sl[1]))

        for unidade in tqdm(unidades, desc=f"verificando unidades do condominio {id_sl[0]}"):
            cobrancas = get_cobrancas_de_unidade(unidade[1], id_sl[1])
            resultado = processar_cobrancas(cobrancas, id_sl[0], unidade)

            if resultado:
                lista_de_cobranca_para_email.append(resultado)
                break  # Para de processar o condomínio ao encontrar a primeira cobrança válida

    if lista_de_cobranca_para_email:
        logger.info("Enviando e-mail com resultados")
        enviar_dados_por_email(lista_de_cobranca_para_email, destinatarios, copiados)
    else:
        logger.info("Nao exite cobranças sem confirmação")

if __name__ == "__main__":
    main()
    
    
    