postgres
		installiert als Service mit postgresql-17-pgvector Extension
		
		

	DBs: 
		n8n - für n8n Server (Sepciern Daten von Workflows)
		n8n_apps -  für Kundenapplikationen , die in N8N Workflows implementiert mit Vector extension "CREATE EXTENSION IF NOT EXISTS vector"
	NUtzung:
		sudo -i -u postgres
		psql 	
		/l DB_NAME  
	install:		
		sudo -i -u postgres

		ALTER USER postgres WITH PASSWORD 'POSTGRESzusammen2019';		
	
	
	
		CREATE USER n8n_user WITH PASSWORD 'N8Nzusammen2019'
		GRANT ALL PRIVILEGES ON DATABASE n8n TO n8n_user;

		
		psql -U n8n_user -d n8n_apps -h localhost -p 5432
		
		
		CREATE EXTENSION IF NOT EXISTS vector;
		CREATE TABLE rag_nutri_documents (
			  id SERIAL PRIMARY KEY,
			  content TEXT NOT NULL,
			  embedding VECTOR(1536),  -- OpenAI embedding dimension
			  metadata JSONB
			);
