Playbook de migração: SQLite → PostgreSQL (PoC)

Este diretório contém um script de migração PoC e instruções.

Pré-requisitos
- Backup do banco SQLite: sempre crie uma cópia do arquivo `.db` antes de migrar.
- Ter um banco PostgreSQL disponível e um usuário com permissões.
- Variáveis de ambiente/credenciais para acessar o Postgres.

Passos básicos
1. Instale dependências (no virtualenv do projeto):

   pip install -r requirements.txt

2. Verifique o banco SQLite:

   sqlite3 /path/to/db.sqlite3 
   "PRAGMA integrity_check;"

3. Execute o script de migração (exemplo):

   python migrations/sqlite_to_postgres/migrate.py --sqlite /path/to/db.sqlite3 --pg "postgresql://user:pass@host:5432/dbname"

4. Valide o resultado no PostgreSQL (contagens, integridade, índices).

Observações e limitações
- O script é um PoC: copia tabelas e dados básicos, mapeando tipos comuns.
- Constraints complexas, triggers, views e procedimentos armazenados podem
  requerer tratamento manual.
- Recomendado: executar migração em ambiente de testes e validar
  comportamento da aplicação antes de promover a produção.

Se precisar, posso adaptar o script para migrar apenas schemas selecionados,
copiar índices/unique/foreign keys e/ou gerar um dump SQL completo.
