query "auth/me" verb=GET {
  api_group = "ACNnorte"
  description = "Retorna o perfil do usuário autenticado."
  auth = "users"

  input {
  }

  stack {
    db.get users {
      field_name = "id"
      field_value = $auth.id
      output = ["id", "created_at", "name", "email", "role", "status"]
    } as $user

    precondition ($user != null) {
      error_type = "notfound"
      error = "Usuário não encontrado."
    }
  }

  response = $user
}
