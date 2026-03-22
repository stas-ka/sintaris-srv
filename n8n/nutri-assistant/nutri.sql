-- Table: public.activation_code_usage_log

-- DROP TABLE IF EXISTS public.activation_code_usage_log;

CREATE TABLE IF NOT EXISTS public.activation_code_usage_log
(
    id integer NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1 ),
    code text COLLATE pg_catalog."default",
    user_id integer,
    usage_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    input_tokens integer,
    output_tokens integer,
    CONSTRAINT activation_code_usage_log_pkey PRIMARY KEY (id),
    CONSTRAINT activation_code_usage_log_code_fkey FOREIGN KEY (code)
        REFERENCES public.activation_codes (code) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT activation_code_usage_log_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES public.tgrm_user (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.activation_code_usage_log
    OWNER to postgres;

REVOKE ALL ON TABLE public.activation_code_usage_log FROM n8n_user;

GRANT SELECT ON TABLE public.activation_code_usage_log TO n8n_user;

GRANT ALL ON TABLE public.activation_code_usage_log TO postgres;


-- Table: public.activation_codes

-- DROP TABLE IF EXISTS public.activation_codes;

CREATE TABLE IF NOT EXISTS public.activation_codes
(
    code text COLLATE pg_catalog."default" NOT NULL,
    user_id integer,
    is_shared boolean NOT NULL DEFAULT false,
    max_requests integer,
    used_requests integer DEFAULT 0,
    max_input_tokens integer,
    used_input_tokens integer DEFAULT 0,
    max_output_tokens integer,
    used_output_tokens integer DEFAULT 0,
    status text COLLATE pg_catalog."default" NOT NULL DEFAULT 'ACTIVE'::text,
    start_time timestamp without time zone[],
    end_time timestamp without time zone,
    activated_at timestamp without time zone,
    CONSTRAINT "activation_codes _pkey" PRIMARY KEY (code),
    CONSTRAINT activation_codes_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES public.tgrm_user (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.activation_codes
    OWNER to n8n_user;

GRANT ALL ON TABLE public.activation_codes TO n8n_user;

COMMENT ON TABLE public.activation_codes
    IS 'ALTER TABLE activation_codes ADD COLUMN is_shared BOOLEAN DEFAULT FALSE;
ALTER TABLE activation_codes ADD COLUMN start_time DATETIME;
ALTER TABLE activation_codes ADD COLUMN end_time DATETIME;
ALTER TABLE activation_codes ADD COLUMN max_requests INTEGER DEFAULT 0;
ALTER TABLE activation_codes ADD COLUMN used_requests INTEGER DEFAULT 0;
ALTER TABLE activation_codes ADD COLUMN max_input_tokens INTEGER DEFAULT 0;
ALTER TABLE activation_codes ADD COLUMN used_input_tokens INTEGER DEFAULT 0;
ALTER TABLE activation_codes ADD COLUMN max_output_tokens INTEGER DEFAULT 0;
ALTER TABLE activation_codes ADD COLUMN used_output_tokens INTEGER DEFAULT 0;
ALTER TABLE activation_codes ADD COLUMN status TEXT DEFAULT ''ACTIVE'';';

COMMENT ON COLUMN public.activation_codes.max_requests
    IS '
';

COMMENT ON COLUMN public.activation_codes.status
    IS 'new
used
not_active';

-- Table: public.embedding_collections

-- DROP TABLE IF EXISTS public.embedding_collections;

CREATE TABLE IF NOT EXISTS public.embedding_collections
(
    uuid uuid NOT NULL DEFAULT uuid_generate_v4(),
    name character varying COLLATE pg_catalog."default",
    cmetadata jsonb,
    CONSTRAINT embedding_collections_pkey PRIMARY KEY (uuid)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.embedding_collections
    OWNER to n8n_user;

GRANT ALL ON TABLE public.embedding_collections TO n8n_user;
-- Index: idx_embedding_collections_name

-- DROP INDEX IF EXISTS public.idx_embedding_collections_name;

CREATE INDEX IF NOT EXISTS idx_embedding_collections_name
    ON public.embedding_collections USING btree
    (name COLLATE pg_catalog."default" ASC NULLS LAST)
    TABLESPACE pg_default;
	
	
	
-- Table: public.inteligentnutritionist_bot_chat_histories

-- DROP TABLE IF EXISTS public.inteligentnutritionist_bot_chat_histories;

CREATE TABLE IF NOT EXISTS public.inteligentnutritionist_bot_chat_histories
(
    id integer NOT NULL DEFAULT nextval('inteligentnutritionist_bot_chat_histories_id_seq'::regclass),
    session_id character varying(255) COLLATE pg_catalog."default" NOT NULL,
    message jsonb NOT NULL,
    requested_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT inteligentnutritionist_bot_chat_histories_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.inteligentnutritionist_bot_chat_histories
    OWNER to n8n_user;

GRANT ALL ON TABLE public.inteligentnutritionist_bot_chat_histories TO n8n_user;

-- Table: public.rag_nutri_documents

-- DROP TABLE IF EXISTS public.rag_nutri_documents;

CREATE TABLE IF NOT EXISTS public.rag_nutri_documents
(
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    text text COLLATE pg_catalog."default",
    metadata jsonb,
    embedding vector,
    CONSTRAINT rag_nutri_documents_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.rag_nutri_documents
    OWNER to n8n_user;

GRANT ALL ON TABLE public.rag_nutri_documents TO n8n_user;

-- Table: public.tgrm_user

-- DROP TABLE IF EXISTS public.tgrm_user;

CREATE TABLE IF NOT EXISTS public.tgrm_user
(
    id integer NOT NULL,
    user_name text COLLATE pg_catalog."default",
    first_name text COLLATE pg_catalog."default",
    last_name text COLLATE pg_catalog."default",
    full_name text COLLATE pg_catalog."default",
    bot boolean DEFAULT false,
    chat_id integer,
    "desc" text COLLATE pg_catalog."default",
    source text COLLATE pg_catalog."default",
    start_params text COLLATE pg_catalog."default",
    create_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    last_action text COLLATE pg_catalog."default",
    active text COLLATE pg_catalog."default",
    CONSTRAINT tgrm_user_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.tgrm_user
    OWNER to n8n_user;

GRANT ALL ON TABLE public.tgrm_user TO n8n_user;
