# Recursos Visuais (Assets)

Esta pasta centraliza os recursos estáticos utilizados nas telas do Streamlit do
projeto ACNnorte. Nenhum arquivo de código é armazenado aqui.

## Estrutura

```text
assets/
├── images/    # Imagens gerais (banners, ilustrações, fundos)
├── icons/     # Ícones avulsos (PNG, SVG, ICO)
├── styles/    # Folhas de estilo e arquivos CSS externos
└── logo/      # Logotipos e variações da marca ACNnorte
```

## Convenções

- Mantenha os nomes dos arquivos em minúsculas, separados por hífen
  (ex.: `logo-acnnorte-horizontal.svg`).
- Prefira formatos vetoriais (`.svg`) para logos e ícones.
- Cada subpasta contém um arquivo `.gitkeep` para preservar a estrutura no Git
  enquanto estiver vazia.
- Os recursos aqui presentes não alteram o funcionamento atual do aplicativo:
  a aplicação continua carregando componentes de `src/ui_components.py`.

## Logotipo oficial

- `images/logo_acnnorte.jpeg` — imagem original oficial (1600 × 405, RGB, MD5
  `c08f849aa93e09496c5f452f151ff365`). É usada no menu lateral, no topo do
  dashboard, nas demais telas internas e no login. O arquivo é exibido sem
  recorte, filtros ou efeitos, com proporção preservada por `object-fit: contain`
  e largura responsiva; o fundo branco do JPEG é apresentado como um cartão
  discreto sobre o fundo `#F3F4F6` do aplicativo.
- `logo/acnnorte_logo.svg` — redesenho vetorial antigo, mantido no repositório,
  mas atualmente sem uso pela aplicação.
- Ambos os caminhos são carregados por `render_acnnorte_logo(...)` em
  `src/ui_components.py`. A tela de login passa explicitamente
  `logo_path=LOGIN_LOGO_PATH`; as demais telas usam `LOGO_PATH`. Caso o arquivo
  não esteja disponível, a função exibe um fallback textual com a paleta
  institucional.

## Observação

Os demais recursos seguem disponíveis para futuras melhorias de experiência do
usuário. Nenhum import, funcionalidade, armazenamento de dados ou autenticação
foi modificado pela inclusão do logotipo.

