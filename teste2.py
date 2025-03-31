import requests
from bs4 import BeautifulSoup

get_header = {
    'Content-Type': 'application/json',
    'app_token': 'abcaac41-b011-4dad-bf94-d078eb4e3cc2',
    'access_token': '10c4f4d3-894b-480b-a84e-fade81415b7c'    
}

def get_all_links():
    url = 'https://admin109683.superlogica.net/clients/condor/impressoes/index?idCondominio=-1&doTipo=remessa'
    
    # Fazendo a requisição
    response = requests.get(url, get_header)
    
    # Verificando se a requisição foi bem-sucedida
    if response.status_code != 200:
        print("Erro ao acessar a página")
        return
    
    # Parseando o conteúdo HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Coletando todos os links
    links = []
    for a_tag in soup.find_all('a', href=True):
        links.append(a_tag['href'])
    
    return links

# Executando a função
all_links = get_all_links()
print(all_links)
