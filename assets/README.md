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

- `logo/acnnorte_logo.svg` — marca vetorial usada no menu lateral e nas telas internas.
- `images/logo_acnnorte.jpeg` — imagem original oficial (1600 × 405) usada na
  tela de login. O arquivo é exibido sem recorte ou efeitos, com proporção
  preservada por `object-fit: contain` e largura responsiva.
- Ambos são carregados por `render_acnnorte_logo(...)` em `src/ui_components.py`.
  A tela de login passa explicitamente `logo_path=LOGIN_LOGO_PATH`; as demais
  telas continuam usando o SVG. Caso o arquivo não esteja disponível, a função
  exibe um fallback textual com a paleta institucional.

## Observação

Os demais recursos seguem disponíveis para futuras melhorias de experiência do
usuário. Nenhum import, funcionalidade, armazenamento de dados ou autenticação
foi modificado pela inclusão do logotipo.

