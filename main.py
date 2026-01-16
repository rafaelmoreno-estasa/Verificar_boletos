import requests
import json
import time
from superlogica_chamadas_API.preparo_condominio import PreparoCondominio
from rammer_utils.utils.email import enviar_email, criar_email
from rammer_utils.utils.log import init_main_logger
from rammer_utils.utils.config import Config
import logging
from tqdm import tqdm
import re
from datetime import datetime, timedelta, date

logger = init_main_logger('verificar_cobranças')

get_header = {
    'Content-Type': 'application/json',
    'app_token': 'abcaac41-b011-4dad-bf94-d078eb4e3cc2',
    'access_token': '10c4f4d3-894b-480b-a84e-fade81415b7c'    
}






def primeiro_e_ultimo_dia_do_mes(data=None):
    if data is None:
        data = date.today()
    primeiro_dia = data.replace(day=1)
    if data.month == 12:
        proximo_mes = data.replace(year=data.year + 1, month=1, day=1)
    else:
        proximo_mes = data.replace(month=data.month + 1, day=1)
    ultimo_dia = proximo_mes - timedelta(days=1)
    return (
        primeiro_dia.strftime("%m/%d/%Y"),
        ultimo_dia.strftime("%m/%d/%Y")
    )



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

    datas = primeiro_e_ultimo_dia_do_mes()

#    logger.info(f"Verificando documentos para o condomínio ID: {id_sl}")

    while True:
        url = f'https://api.superlogica.net/v2/condor/impressoes/index?idCondominio={id_sl}&publicadoApenasPara=administracao&dtInicio={datas[0]}&dtFim={datas[1]}&itensPorPagina=50&pagina={page}&comStatus=atuais'
        response = requests.get(url, headers=get_header, timeout=10)

        if response.status_code != 200:
            logger.error(f"Erro ao acessar a API para condomínio {id_sl}: {response.status_code}")
            break

        data = response.json()
        if id_sl == '234':
            print("vamos lá")
        hoje = datetime.today().date()  
        cinco_dias_atras = hoje - timedelta(days=6) 
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
                if id_impressao_fimp == 'e0302312':
                    print("achei")
                with open(f'documento_temporario.txt', 'wb') as f:
                    f.write(response.content)

                enderecos = extrair_enderecos(f'documento_temporario.txt')

                return enderecos
            except:
                pass
        except:
            pass

def get_codigo_from_enderecos(enderecos):
    codigos_cond = set()  # Usando um set para evitar duplicados
    endereco_erro = []
    for endereco in enderecos:
        response = requests.get(f"https://servidor-webapp.estasa.net:8085/apisqlserver/get_condominio_by_address?endereco={endereco.get('endereco')}", verify=False)

        if response.status_code == 200:
            all_adress = response.json()
            if all_adress:
                codigo = all_adress.get('codigo')
                if codigo:
                    codigos_cond.add(codigo)  # Adiciona no set
        else:
            endereco_erro.append(endereco)
    
    logger.error(endereco_erro)
    return list(codigos_cond)  # Converte para lista no retorno

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
    try:
        response = requests.get(url, headers=get_header, timeout=10)
        time.sleep(1.5)  # Respeitar limite de requisição da API
    
        if response.status_code != 200:
            return []
        
        return response.json()
    except Exception as e:
        logger.info(f"Erro ao pegar a cobrança de uma unidade : {e}")
    
        logger.error(f"Erro ao acessar a API para unidade {id_unidade}")
        return []

def processar_cobrancas(cobrancas, codigo_cond, unidade):
    for pendente in cobrancas:
        status = pendente.get("fl_remessastatus_recb")
        if status in ['2', '0']:
            

            return {
                "condominio": codigo_cond,
                "unidade": unidade[0],
                "id_unidade": unidade[1],
                "fl_status_recb": pendente.get("fl_status_recb", "N/A"),
                "fl_remessastatus_recb": status,
                "dt_geracao_recb" : pendente.get('dt_geracao_recb', 'N/A'),
                "id_recebimento_recb": pendente.get("id_recebimento_recb", "N/A"),
                "st_documento_recb": pendente.get("st_documento_recb", "N/A"),
                "dt_vencimento_recb": pendente.get("dt_vencimento_recb", "N/A"),
                "vl_total_recb": pendente.get("vl_total_recb", "N/A"),
                "st_label_recb" :pendente.get("st_label_recb", "")
            }
    return None

def enviar_dados_por_email_operacional(lista_resultados, destinatarios, copiados):
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
            <p>
            Esta planilha contém cobranças sem retorno bancário emitidas pelo time da Operacional.
            Caso identifique alguma cobrança que não tenha sido emitida pela Operacional, entre em contato com o time de desenvolvedores pelo e-mail devs@estasa.com.br para que possamos corrigir o programa.</p>
                <table>
                <tr>
                    <th>Condomínio</th>
                    <th>Vencimento</th>
                    <th>Data da Criação da Cobrança</th>
                    <th>ID da cobrança</th>
                </tr>
    """
    
    for resultado in lista_resultados:
        condominio = str(resultado.get("condominio", "N/A")).zfill(4)
        dt_vencimento_str = resultado.get("dt_vencimento_recb", "N/A")
        dt_vencimento = dt_vencimento_str.split()[0]
        data_str = resultado.get("dt_geracao_recb").split()[0]
        data_obj = datetime.strptime(data_str, "%m/%d/%Y")   
        dt_geracao_recb = data_obj.strftime("%d/%m/%Y")
        dt_vencimento = datetime.strptime(dt_vencimento, "%m/%d/%Y").strftime("%d/%m/%Y")
        id_recebimento_recb = resultado.get('id_recebimento_recb', "N/A")
        corpo += f"""
                <tr>
                    <td>{condominio}</td>
                    <td>{dt_vencimento}</td>
                    <td>{dt_geracao_recb}</td>
                    <td>{id_recebimento_recb}</td>
                </tr>
        """

    corpo += """
            </table>
        </body>
    </html>
    """
    
    corpo += """</ul></body></html>"""
    mail = criar_email(assunto='(Superlogica) Cobranças Sem Retorno Bancário OPERACIONAL - Verificação Necessária', corpo=corpo, destinatarios=destinatarios, copiados=copiados)
    enviar_email(mail)
    return True



def enviar_dados_por_email_operacional_e_cac(lista_resultados, destinatarios_cac, destinatarios_operacional, copiados):
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
            <h2>Condomínios com Cobranças sem Retorno Bancário</h2>
            <p>
                Abaixo estão listados os condomínios com a quantidade de cobranças que ainda não possuem retorno bancário.<br>
            </p>
            <table>
                <tr>
                    <th>ID do Condomínio</th>
                    <th>Quantidade de Unidades sem Retorno</th>
                </tr>
    """

    for id_condominio, quantidade in lista_resultados:
        id_formatado = str(id_condominio).zfill(4)
        corpo += f"""
                <tr>
                    <td>{id_formatado}</td>
                    <td>{quantidade}</td>
                </tr>
        """

    corpo += """
            </table>
        </body>
    </html>
    """

    # Envia para CAC + Operacional
    destinatarios = destinatarios_cac + destinatarios_operacional

    mail = criar_email(
        assunto='(Superlogica) Cobranças Sem Retorno Bancário - Verificação Necessária',
        corpo=corpo,
        destinatarios=destinatarios,
        copiados=copiados
    )

    enviar_email(mail)
    return True


def enviar_dados_por_email_CAC(lista_resultados, destinatarios, copiados):
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
            <p>
                Esta planilha contém cobranças sem retorno bancário emitidas pelo time da CAC.
                Caso identifique alguma cobrança que não tenha sido emitida pela CAC, entre em contato com o time de desenvolvedores pelo e-mail devs@estasa.com.br para que possamos corrigir o programa.
            </p>
            <table>
                <tr>
                    <th>Condominio</th>
                    <th>Data de Vencimento</th>
                    <th>Data da Criação do Cobrança</th>
                    <th>ID da cobrança</th>
                </tr>
    """
    
    for resultado in lista_resultados:
        condominio = str(resultado.get("condominio", "N/A")).zfill(4)
        dt_vencimento_str = resultado.get("dt_vencimento_recb", "N/A")
        dt_vencimento = dt_vencimento_str.split()[0]
        dt_vencimento = datetime.strptime(dt_vencimento, "%m/%d/%Y").strftime("%d/%m/%Y")
        dt_geracao_recb = resultado.get("dt_geracao_recb","N/A").split()[0]
        dt_geracao_recb = datetime.strptime(dt_geracao_recb, "%m/%d/%Y").strftime("%d/%m/%Y")
        id_recebimento_recb = resultado.get('id_recebimento_recb', "N/A")
        corpo += f"""
                <tr>
                    <td>{condominio}</td>
                    <td>{dt_vencimento}</td>
                    <td>{dt_geracao_recb}</td>
                    <td>{id_recebimento_recb}</td>
                </tr>
        """
    corpo += """
            </table>
        </body>
    </html>
    """
    
    corpo += """</ul></body></html>"""
    mail = criar_email(assunto='(Superlogica) Cobranças Sem Retorno Bancário CAC - Verificação Necessária', corpo=corpo, destinatarios=destinatarios, copiados=copiados)
    enviar_email(mail)
    return True



def main():
    conds = get_all_condominios()
    
    
    info_documentos_de_cobranca = []

    logger.info("Iniciando a verificação de documentos para todos os condomínios")

    for cond in tqdm(conds, desc="Verificando documentos dos condomínios"):
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

    lista_de_cobranca_para_email_cac = []
    lista_de_cobranca_para_email_operacional = []
    lista_de_cobranca_para_email_cac_e_operacional = []
    config = ler_configuracao()
    destinatarios_cac = config.get('destinatarios_cac')
    destinatarios_operacional = config.get('destinatarios_operacional')
    copiados = config.get('copiados')

    for id_sl in tqdm(tuplas_codigo_id, desc="Verificando as cobranças de cada condomino"):
        unidades = search_id_unidades(get_unidades(id_sl[1]))
        unidades_sem_retorno = []
        for unidade in tqdm(unidades, desc=f"verificando unidades do condominio {id_sl[0]}"):
            cobrancas = get_cobrancas_de_unidade(unidade[1], id_sl[1])
            resultado = processar_cobrancas(cobrancas, id_sl[0], unidade)
            
            if resultado:
                    if resultado.get('st_label_recb') in ['ACORDO','INADIMPLENTE']:
                        datahoje = datetime.now()
                        vencimento_str = resultado.get('dt_vencimento_recb').split()[0]
                        vencimento = datetime.strptime(vencimento_str.replace('/', '-'), '%m-%d-%Y')
                        if vencimento > datahoje:
                            lista_de_cobranca_para_email_cac.append(resultado)
                        else:
                            logger.info(resultado)
                    else:
                        unidades_sem_retorno.append(resultado)
        if len(unidades) == len(unidades_sem_retorno):
            lista_de_cobranca_para_email_operacional.append((id_sl[0], len(unidades_sem_retorno)))
            
        if len(unidades_sem_retorno) > 1 and len(unidades_sem_retorno) < len(unidades):
            lista_de_cobranca_para_email_cac_e_operacional(id_sl[0], len(unidades_sem_retorno) )
    if lista_de_cobranca_para_email_cac_e_operacional:
        logger.info("Enviando um email com os resultados para cac e operacional")
        enviar_dados_por_email_operacional_e_cac(lista_de_cobranca_para_email_cac_e_operacional, destinatarios_cac, destinatarios_operacional, copiados)
    if lista_de_cobranca_para_email_cac:
        logger.info("Enviando e-mail com resultados para o cac")
        enviar_dados_por_email_CAC(lista_de_cobranca_para_email_cac, destinatarios_cac, copiados)
    if lista_de_cobranca_para_email_operacional:
        logger.info("Enviando e-mail com resultados para o operacional")
        enviar_dados_por_email_operacional(lista_de_cobranca_para_email_operacional, destinatarios_operacional, copiados)
    else:
        logger.info("Nao exite cobranças sem confirmação")

if __name__ == "__main__":
    main()
    
    
    