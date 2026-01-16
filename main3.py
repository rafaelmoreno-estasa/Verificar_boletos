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
import aiohttp
import asyncio
import certifi, ssl

ssl_context = ssl.create_default_context(cafile=certifi.where())
logger = init_main_logger('verificar_cobranças')

get_header = {
    'Content-Type': 'application/json',
    'app_token': 'abcaac41-b011-4dad-bf94-d078eb4e3cc2',
    'access_token': '10c4f4d3-894b-480b-a84e-fade81415b7c'    
}

sem = asyncio.Semaphore(10)

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

def enviar_dados_por_email_operacional(lista_resultados, destinatarios_operacional, copiados):
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
                Abaixo estão listados os condomínios em que o número de cobranças sem retorno bancário corresponde à quantidade total de unidades.<br>
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

    # Envia para Operacional
    destinatarios = destinatarios_operacional

    mail = criar_email(
        assunto='(Superlogica) Cobranças Sem Retorno Bancário OPERACIONAL - Verificação Necessária',
        corpo=corpo,
        destinatarios=destinatarios,
        copiados=copiados
    )

    enviar_email(mail)
    return True


def ler_configuracao(caminho_arquivo="configuracao.json", ambiente="[GERAL]"):
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
            configuracao = json.load(arquivo)
        return configuracao.get(ambiente, {})
    except (FileNotFoundError, json.JSONDecodeError):
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
    while True:
        url = f'https://api.superlogica.net/v2/condor/impressoes/index?idCondominio={id_sl}&publicadoApenasPara=administracao&dtInicio={datas[0]}&dtFim={datas[1]}&itensPorPagina=50&pagina={page}&comStatus=atuais'
        response = requests.get(url, headers=get_header, timeout=10)
        if response.status_code != 200:
            break
        data = response.json()
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
            id_impressao_fimp = doc.get('id_impressao_fimp')
            response = requests.get(url = f'https://api.superlogica.net/v2/condor/documentos/download?id={id_impressao_fimp}', headers=get_header)
            with open('documento_temporario.txt', 'wb') as f:
                f.write(response.content)
            enderecos = extrair_enderecos('documento_temporario.txt')
            return enderecos
        except:
            continue

def get_codigo_from_enderecos(enderecos):
    codigos_cond = set()
    for endereco in enderecos:
        response = requests.get(f"https://servidor-webapp.estasa.net:8085/apisqlserver/get_condominio_by_address?endereco={endereco.get('endereco')}", verify=False)
        if response.status_code == 200:
            all_adress = response.json()
            codigo = all_adress.get('codigo')
            if codigo:
                codigos_cond.add(codigo)
    return list(codigos_cond)

def search_id_unidades(unidades):
    return [(unidade['st_unidade_uni'], unidade['id_unidade_uni']) for unidade in unidades]

async def get_unidades_async(session, id_sl):
    unidades = []
    page = 1
    while True:
        url = f'https://api.superlogica.net/v2/condor/unidades/index?idCondominio={id_sl}&exibirGruposDasUnidades=1&itensPorPagina=50&pagina={page}&exibirDadosDosContatos=1'
        await asyncio.sleep(2.5)
        async with session.get(url, headers=get_header, ssl=ssl_context) as response:
            if response.status != 200:
                break
            data = await response.json()
            unidades.extend(data)
            if len(data) < 50:
                break
            page += 1
    return unidades

async def get_cobrancas_de_unidade_async(session, id_unidade, id_sl):
    hoje = datetime.today()
    primeiro_dia = hoje.replace(day=1).strftime("%m/01/%Y")
    proximo_mes = hoje.replace(day=28) + timedelta(days=4)
    ultimo_dia = proximo_mes.replace(day=1) - timedelta(days=1)
    ultimo_dia_str = ultimo_dia.strftime("%m/%d/%Y")
    url = (f'https://api.superlogica.net/v2/condor/cobranca/index?status=pendentes'
           f'&apenasColunasPrincipais=1&exibirPgtoComDiferenca=1&comContatosDaUnidade=1'
           f'&idCondominio={id_sl}&dtInicio={primeiro_dia}&dtFim={ultimo_dia_str}'
           f'&UNIDADES[0]={id_unidade}&itensPorPagina=50&pagina=1')
    try:
        async with session.get(url, headers=get_header, ssl=ssl_context) as response:
            
            if response.status != 200:
                return []
            return await response.json()
    except:
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

async def processar_condominio(session, id_sl, conds, lista_cac, lista_op, lista_cac_op):
    async with sem:
        try:
            unidades = search_id_unidades(await get_unidades_async(session, id_sl[1]))
            unidades_sem_retorno = []
            for unidade in unidades:
                cobrancas = await get_cobrancas_de_unidade_async(session, unidade[1], id_sl[1])
                resultado = processar_cobrancas(cobrancas, id_sl[0], unidade)
                if resultado:
                    if resultado.get('st_label_recb') in ['ACORDO','INADIMPLENTE']:
                        vencimento_str = resultado.get('dt_vencimento_recb').split()[0]
                        vencimento = datetime.strptime(vencimento_str.replace('/', '-'), '%m-%d-%Y')
                        if vencimento > datetime.now():
                            lista_cac.append(resultado)
                        else:
                            logger.info(resultado)
                    else:
                        unidades_sem_retorno.append(resultado)
            if len(unidades) == len(unidades_sem_retorno):
                lista_op.append((id_sl[0], len(unidades_sem_retorno)))
            elif len(unidades_sem_retorno) > 1:
                lista_cac_op.append((id_sl[0], len(unidades_sem_retorno)))
        except Exception as e:
            logger.error(f"Erro ao processar condomínio {id_sl}: {e}")

def main():
    conds = get_all_condominios()
    info_documentos_de_cobranca = []
    for cond in tqdm(conds, desc="Verificando documentos dos condomínios"):
        documentos = verificar_documentos_de_um_condominio(cond.get("id_condominio_cond"))
        if documentos:
            info_documentos_de_cobranca.append(documentos)
    dic_lista_de_endereco = []
    for doc in tqdm(info_documentos_de_cobranca, desc="verificao de informação de doc"):
        doc_de_cobranca_processado = processar_doc_cobranca(doc)
        if doc_de_cobranca_processado:
            dic_lista_de_endereco.extend(doc_de_cobranca_processado)
    codigos = get_codigo_from_enderecos(dic_lista_de_endereco)
    tuplas_codigo_id = [(codigo, cond.get('id_condominio_cond')) for codigo in codigos for cond in conds if str(codigo) == cond.get('st_label_cond')]
    lista_cac = []
    lista_op = []
    lista_cac_op = []
    config = ler_configuracao()
    destinatarios_cac = config.get('destinatarios_cac')
    destinatarios_operacional = config.get('destinatarios_operacional')
    copiados = config.get('copiados')

    async def verificar_condominios():
        async with aiohttp.ClientSession() as session:
            tasks = [processar_condominio(session, id_sl, conds, lista_cac, lista_op, lista_cac_op) for id_sl in tuplas_codigo_id]
            await asyncio.gather(*tasks)

    asyncio.run(verificar_condominios())

    if lista_cac_op:
        logger.info("Enviando email CAC + Operacional")
        enviar_dados_por_email_operacional_e_cac(lista_cac_op, destinatarios_cac, destinatarios_operacional, copiados)
    if lista_cac:
        logger.info("Enviando email CAC")
        enviar_dados_por_email_CAC(lista_cac, destinatarios_cac, copiados)
    if lista_op:
        logger.info("Enviando email Operacional")
        enviar_dados_por_email_operacional(lista_op, destinatarios_operacional, copiados)
    if not (lista_cac or lista_op or lista_cac_op):
        logger.info("Não existem cobranças sem confirmação")

if __name__ == "__main__":
    main()
