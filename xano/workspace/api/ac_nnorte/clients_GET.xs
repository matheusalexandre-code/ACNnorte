query "clients" verb=GET {
  api_group = "ACNnorte"
  description = "Lista clientes ativos com filtros opcionais por nome ou CNPJ."
  auth = "users"

  input {
    text name?
    text cnpj?
    int page?=1
    int per_page?=50
  }

  stack {
    db.query clients {
      where = $db.clients.active == true
      sort = {name: "asc"}
      return = {
        type: "list"
        paging: {
          page: $input.page
          per_page: $input.per_page
          totals: true
          metadata: true
        }
      }
    } as $clients
  }

  response = $clients
}
