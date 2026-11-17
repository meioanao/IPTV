# Lista IPTV Unificada (Auto-Update)

Projeto automatizado em Python + GitHub Actions que baixa, unifica, remove duplicados, categoriza em português e verifica a disponibilidade (online/offline) de listas M3U públicas a cada 12 horas.

## Categorias Geradas (`group-title`)
- **Brasil Abertos**
- **Filmes e Séries BR**
- **Esportes**
- **EUA Abertos**
- **Filmes e Séries EUA**

## Estrutura do Projeto
- `update_playlist.py`: Script principal que baixa as 7 listas, remove links duplicados, testa os streams em paralelo (`concurrent.futures` com timeout de 5s) e gera os arquivos finais.
- `docs/lista_unificada.m3u`: Lista M3U limpa e pronta para uso em qualquer player IPTV.
- `docs/index.html`: Página web com estatísticas de canais ativos e link direto da lista.
- `.github/workflows/update.yml`: Workflow do GitHub Actions que executa a cada 12 horas (`0 */12 * * *`) ou manualmente via `workflow_dispatch`, fazendo commit automático e publicando no GitHub Pages.
